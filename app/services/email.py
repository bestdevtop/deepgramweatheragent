import smtplib
from email.mime.text import MIMEText

from app.config import settings
from app.services.runtime_config import get_recipient_email
from app.services.weather import build_sms_message


class EmailError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def email_configured() -> bool:
    return bool(
        settings.from_email
        and get_recipient_email()
        and settings.smtp_password
    )


def send_coat_reminder_email(weather: dict) -> None:
    if not email_configured():
        raise EmailError("Email is not configured.")

    city_name = weather["name"]
    body = build_sms_message(weather)
    message = MIMEText(body)
    message["Subject"] = f"Coat Reminder — {city_name}"
    recipient = get_recipient_email()
    message["From"] = settings.from_email
    message["To"] = recipient

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
        server.starttls()
        server.login(settings.from_email, settings.smtp_password)
        server.sendmail(settings.from_email, [recipient], message.as_string())


def send_test_email(recipient: str | None = None) -> str:
    if not email_configured():
        raise EmailError("Email is not configured.")

    to_address = (recipient or get_recipient_email()).strip()
    if not to_address:
        raise EmailError("Recipient email is required.")

    sample_weather = {
        "name": "Test City",
        "main": {"temp": 42},
        "weather": [{"description": "cloudy"}],
    }
    city_name = sample_weather["name"]
    body = build_sms_message(sample_weather)
    message = MIMEText(body)
    message["Subject"] = f"Coat Reminder — {city_name} (Test)"
    message["From"] = settings.from_email
    message["To"] = to_address

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
        server.starttls()
        server.login(settings.from_email, settings.smtp_password)
        server.sendmail(settings.from_email, [to_address], message.as_string())

    return to_address

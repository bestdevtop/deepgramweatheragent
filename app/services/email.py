import smtplib
from email.mime.text import MIMEText

from app.config import settings
from app.services.weather import build_sms_message


class EmailError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def email_configured() -> bool:
    return bool(
        settings.from_email
        and settings.to_email
        and settings.smtp_password
    )


def send_coat_reminder_email(weather: dict) -> None:
    if not email_configured():
        raise EmailError("Email is not configured.")

    city_name = weather["name"]
    body = build_sms_message(weather)
    message = MIMEText(body)
    message["Subject"] = f"Coat Reminder — {city_name}"
    message["From"] = settings.from_email
    message["To"] = settings.to_email

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
        server.starttls()
        server.login(settings.from_email, settings.smtp_password)
        server.sendmail(settings.from_email, [settings.to_email], message.as_string())

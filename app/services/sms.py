from twilio.rest import Client

from app.config import settings
from app.services.weather import build_sms_message


class SmsError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def twilio_configured() -> bool:
    return bool(
        settings.twilio_account_sid
        and settings.twilio_auth_token
        and settings.twilio_from_number
    )


def send_coat_reminder(weather: dict, to_number: str) -> None:
    if not twilio_configured():
        raise SmsError("Twilio is not configured.")
    if not to_number:
        raise SmsError("Recipient phone number is required.")

    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    client.messages.create(
        body=build_sms_message(weather),
        from_=settings.twilio_from_number,
        to=to_number,
    )

"""Runtime settings that can be changed from the UI without restarting."""

from app.config import settings

_recipient_email: str | None = None


def get_recipient_email() -> str:
    if _recipient_email:
        return _recipient_email
    return settings.to_email


def set_recipient_email(email: str) -> None:
    global _recipient_email
    _recipient_email = email.strip()


def reset_recipient_email() -> None:
    global _recipient_email
    _recipient_email = None

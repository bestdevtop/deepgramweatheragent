from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field

from app.config import settings
from app.services.email import EmailError, send_test_email
from app.services.runtime_config import get_recipient_email, set_recipient_email

router = APIRouter(tags=["config"])


class ConfigResponse(BaseModel):
    twilio_from_number: str
    from_email: str
    recipient_email: str


class RecipientEmailUpdate(BaseModel):
    recipient_email: EmailStr = Field(..., description="Email address for coat reminders")


class SendTestEmailRequest(BaseModel):
    recipient_email: EmailStr | None = Field(
        default=None,
        description="Optional recipient override; uses saved recipient when omitted",
    )


class SendTestEmailResponse(BaseModel):
    message: str
    recipient_email: str


@router.get("/config", response_model=ConfigResponse)
def get_config():
    return ConfigResponse(
        twilio_from_number=settings.twilio_from_number,
        from_email=settings.from_email,
        recipient_email=get_recipient_email(),
    )


@router.put("/config/recipient-email", response_model=ConfigResponse)
def update_recipient_email(body: RecipientEmailUpdate):
    set_recipient_email(body.recipient_email)
    return ConfigResponse(
        twilio_from_number=settings.twilio_from_number,
        from_email=settings.from_email,
        recipient_email=get_recipient_email(),
    )


@router.post("/config/send-test-email", response_model=SendTestEmailResponse)
def send_test_email_endpoint(body: SendTestEmailRequest | None = None):
    recipient = body.recipient_email if body else None
    try:
        sent_to = send_test_email(recipient)
    except EmailError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to send test email.") from exc

    return SendTestEmailResponse(
        message=f"Test coat reminder sent to {sent_to}.",
        recipient_email=sent_to,
    )

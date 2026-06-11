import asyncio
import logging

from app.services.email import email_configured, send_coat_reminder_email
from app.services.sms import send_coat_reminder, twilio_configured
from app.services.weather import WeatherError, build_weather_response, fetch_weather

logger = logging.getLogger(__name__)


def _normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    phone = str(phone).strip()
    if not phone.startswith("+"):
        digits = "".join(ch for ch in phone if ch.isdigit())
        if digits:
            phone = f"+{digits}"
    return phone or None


async def dispatch_function(
    name: str,
    args: dict,
    caller_phone: str | None = None,
) -> dict:
    if name == "check_weather":
        return await _check_weather(args, caller_phone)

    if name == "end_call":
        reason = args.get("reason", "customer_goodbye")
        logger.info("Call ending: %s", reason)
        return {"status": "call_ended", "reason": reason}

    logger.warning("Unknown function: %s", name)
    return {"error": f"Unknown function: {name}"}


async def _check_weather(args: dict, caller_phone: str | None) -> dict:
    city = (args.get("city") or "").strip()
    if not city:
        return {"message": "I couldn't find a city name. Which town would you like me to check?"}

    try:
        weather = await fetch_weather(city)
    except WeatherError as exc:
        return {"message": exc.message}

    result = build_weather_response(weather)
    if not result["is_cold"]:
        return result

    phone = _normalize_phone(caller_phone)

    async def try_sms() -> bool:
        if not (phone and twilio_configured()):
            if not phone:
                logger.warning("Cold weather for %s but no caller phone available.", city)
            return False
        try:
            await asyncio.to_thread(send_coat_reminder, weather, phone)
            return True
        except Exception:
            logger.exception("Failed to send Twilio SMS for city=%s", city)
            return False

    async def try_email() -> bool:
        if not email_configured():
            return False
        try:
            await asyncio.to_thread(send_coat_reminder_email, weather)
            return True
        except Exception:
            logger.exception("Failed to send email coat reminder for city=%s", city)
            return False

    sms_sent, email_sent = await asyncio.gather(try_sms(), try_email())

    return build_weather_response(weather, sms_sent=sms_sent, email_sent=email_sent)

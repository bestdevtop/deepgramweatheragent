import json
import logging

from fastapi import APIRouter, Request, Response, WebSocket

from app.config import settings
from app.voice_agent.session import VoiceAgentSession

logger = logging.getLogger(__name__)

router = APIRouter(tags=["telephony"])

_twilio_validator = None
if settings.twilio_auth_token:
    from twilio.request_validator import RequestValidator

    _twilio_validator = RequestValidator(settings.twilio_auth_token)

active_sessions: dict[str, VoiceAgentSession] = {}


def _check_webhook_secret(token: str | None) -> bool:
    if not settings.webhook_secret:
        return True
    return token == settings.webhook_secret


def _build_ws_path() -> str:
    if settings.webhook_secret:
        return f"/twilio/{settings.webhook_secret}"
    return "/twilio"


@router.post("/incoming-call")
@router.post("/incoming-call/{token}")
async def incoming_call(request: Request, token: str | None = None) -> Response:
    if not _check_webhook_secret(token):
        return Response(status_code=404)

    form_data = await request.form()
    params = dict(form_data)

    if _twilio_validator:
        url = str(request.url)
        signature = request.headers.get("X-Twilio-Signature", "")
        if not _twilio_validator.validate(url, params, signature):
            logger.warning("[TELEPHONY] Invalid Twilio signature - rejecting request")
            return Response(status_code=404)

    caller_from = params.get("From", "")

    if settings.server_external_url:
        host = settings.server_external_url.replace("https://", "").replace("http://", "").rstrip("/")
    else:
        host = request.headers.get("host", f"localhost:{settings.server_port}")

    ws_path = _build_ws_path()
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="wss://{host}{ws_path}">
            <Parameter name="caller_phone" value="{caller_from}" />
        </Stream>
    </Connect>
</Response>"""

    logger.info("[TELEPHONY] Incoming call - streaming to wss://%s%s", host, ws_path)
    return Response(content=twiml, media_type="application/xml")


@router.websocket("/twilio")
@router.websocket("/twilio/{token}")
async def twilio_websocket(websocket: WebSocket, token: str | None = None):
    if not _check_webhook_secret(token):
        await websocket.close(code=1008)
        return

    await websocket.accept()
    logger.info("[TELEPHONY] WebSocket connected")

    call_sid = None
    stream_sid = None
    caller_phone = None
    session = None

    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)

            if data.get("event") == "start":
                start = data.get("start", {})
                call_sid = start.get("callSid", "unknown")
                stream_sid = start.get("streamSid", "unknown")
                custom = start.get("customParameters", {})
                caller_phone = custom.get("caller_phone")
                logger.info(
                    "[TELEPHONY] Call started - callSid=%s caller=%s",
                    call_sid,
                    caller_phone,
                )
                break
            elif data.get("event") == "connected":
                continue

        session = VoiceAgentSession(websocket, call_sid, stream_sid, caller_phone)
        active_sessions[call_sid] = session

        await session.start()
        await session.run()

    except Exception as exc:
        logger.error("[TELEPHONY] Error in call %s: %s", call_sid, exc)
    finally:
        if session:
            await session.cleanup()
        if call_sid and call_sid in active_sessions:
            del active_sessions[call_sid]
        logger.info("[TELEPHONY] Call %s ended", call_sid)

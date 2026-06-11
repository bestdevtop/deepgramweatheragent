import asyncio
import base64
import json
import logging

from fastapi import WebSocket

from deepgram import AsyncDeepgramClient
from deepgram.agent.v1 import (
    AgentV1AgentAudioDone,
    AgentV1ConversationText,
    AgentV1Error,
    AgentV1FunctionCallRequest,
    AgentV1SendFunctionCallResponse,
    AgentV1SettingsApplied,
    AgentV1UserStartedSpeaking,
    AgentV1Warning,
)
from deepgram.agent.v1.socket_client import V1SocketClientResponse
from deepgram.core.pydantic_utilities import parse_obj_as

from app.config import settings
from app.voice_agent.agent_config import get_agent_config
from app.voice_agent.function_handlers import dispatch_function

logger = logging.getLogger(__name__)


class VoiceAgentSession:
    """Bridges Twilio media stream WebSocket with Deepgram Voice Agent API."""

    def __init__(
        self,
        twilio_ws: WebSocket,
        call_sid: str,
        stream_sid: str,
        caller_phone: str | None = None,
    ):
        self.twilio_ws = twilio_ws
        self.call_sid = call_sid
        self.stream_sid = stream_sid
        self.caller_phone = caller_phone

        self._client = None
        self._connection = None
        self._context_manager = None
        self._settings_applied = asyncio.Event()
        self._cleanup_done = False
        self._listen_task = None
        self._audio_task = None

    async def start(self):
        logger.info("[SESSION:%s] Connecting to Deepgram Voice Agent API", self.call_sid)

        self._client = AsyncDeepgramClient(api_key=settings.deepgram_api_key)
        self._context_manager = self._client.agent.v1.connect()
        self._connection = await self._context_manager.__aenter__()

        self._listen_task = asyncio.create_task(self._listen_loop())

        config = get_agent_config()
        await self._connection.send_settings(config)

        try:
            await asyncio.wait_for(self._settings_applied.wait(), timeout=5.0)
            logger.info("[SESSION:%s] Settings applied - ready for audio", self.call_sid)
        except asyncio.TimeoutError:
            logger.error("[SESSION:%s] Timeout waiting for settings to be applied", self.call_sid)
            raise

    async def run(self):
        self._audio_task = asyncio.create_task(self._forward_twilio_audio())

        done, pending = await asyncio.wait(
            [self._audio_task, self._listen_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        logger.info("[SESSION:%s] Call ended", self.call_sid)

    async def cleanup(self):
        if self._cleanup_done:
            return
        self._cleanup_done = True

        logger.info("[SESSION:%s] Cleaning up", self.call_sid)

        for task in [self._audio_task, self._listen_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        if self._context_manager:
            try:
                await self._context_manager.__aexit__(None, None, None)
            except Exception as exc:
                logger.debug("[SESSION:%s] Error during Deepgram cleanup: %s", self.call_sid, exc)

        self._connection = None
        self._client = None
        logger.info("[SESSION:%s] Cleanup complete", self.call_sid)

    async def _listen_loop(self):
        try:
            async for raw_message in self._connection._websocket:
                try:
                    if isinstance(raw_message, bytes):
                        parsed = raw_message
                    else:
                        json_data = json.loads(raw_message)
                        parsed = parse_obj_as(V1SocketClientResponse, json_data)
                except Exception:
                    msg_type = (
                        json_data.get("type", "unknown")
                        if isinstance(raw_message, str)
                        else "binary"
                    )
                    logger.debug(
                        "[SESSION:%s] Skipping unrecognized message type: %s",
                        self.call_sid,
                        msg_type,
                    )
                    continue

                if isinstance(parsed, AgentV1SettingsApplied):
                    self._settings_applied.set()
                else:
                    await self._handle_message(parsed)
        except Exception as exc:
            logger.info("[SESSION:%s] Deepgram listen loop ended: %s", self.call_sid, exc)
        finally:
            logger.info("[SESSION:%s] Deepgram connection closed", self.call_sid)

    async def _handle_message(self, message):
        try:
            if isinstance(message, bytes):
                audio_b64 = base64.b64encode(message).decode("utf-8")
                await self.twilio_ws.send_json(
                    {
                        "event": "media",
                        "streamSid": self.stream_sid,
                        "media": {"payload": audio_b64},
                    }
                )

            elif isinstance(message, AgentV1FunctionCallRequest):
                await self._handle_function_call(message)

            elif isinstance(message, AgentV1ConversationText):
                logger.info(
                    "[SESSION:%s] %s: %s",
                    self.call_sid,
                    message.role.upper(),
                    message.content,
                )

            elif isinstance(message, AgentV1UserStartedSpeaking):
                logger.info("[SESSION:%s] User started speaking", self.call_sid)
                await self.twilio_ws.send_json(
                    {
                        "event": "clear",
                        "streamSid": self.stream_sid,
                    }
                )

            elif isinstance(message, AgentV1AgentAudioDone):
                logger.debug("[SESSION:%s] Agent finished speaking", self.call_sid)

            elif isinstance(message, AgentV1Error):
                logger.error("[SESSION:%s] Agent error: %s", self.call_sid, message.description)

            elif isinstance(message, AgentV1Warning):
                logger.warning("[SESSION:%s] Agent warning: %s", self.call_sid, message.description)

        except Exception as exc:
            logger.error("[SESSION:%s] Error handling message: %s", self.call_sid, exc)

    async def _handle_function_call(self, event: AgentV1FunctionCallRequest):
        if not event.functions:
            return

        func = event.functions[0]
        function_name = func.name
        call_id = func.id
        args = json.loads(func.arguments) if func.arguments else {}

        logger.info("[SESSION:%s] Function call: %s(%s)", self.call_sid, function_name, args)

        try:
            result = await dispatch_function(
                function_name,
                args,
                caller_phone=self.caller_phone,
            )
            logger.info(
                "[SESSION:%s] Function result: %s -> %s",
                self.call_sid,
                function_name,
                json.dumps(result),
            )
        except Exception as exc:
            logger.error(
                "[SESSION:%s] Function error: %s -> %s",
                self.call_sid,
                function_name,
                exc,
            )
            result = {"error": str(exc)}

        response = AgentV1SendFunctionCallResponse(
            type="FunctionCallResponse",
            name=function_name,
            content=json.dumps(result),
            id=call_id,
        )
        await self._connection.send_function_call_response(response)

        if function_name == "end_call":
            asyncio.create_task(self._end_call_after_delay())

    async def _end_call_after_delay(self):
        await asyncio.sleep(3)
        logger.info("[SESSION:%s] Hanging up call", self.call_sid)

        if settings.twilio_account_sid and settings.twilio_auth_token:
            try:
                from twilio.rest import Client

                client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
                await asyncio.to_thread(
                    client.calls(self.call_sid).update,
                    status="completed",
                )
                logger.info("[SESSION:%s] Twilio call completed", self.call_sid)
            except Exception as exc:
                logger.error("[SESSION:%s] Failed to complete Twilio call: %s", self.call_sid, exc)

        try:
            await self.twilio_ws.close()
        except Exception:
            pass

    async def _forward_twilio_audio(self):
        try:
            while True:
                message = await self.twilio_ws.receive_text()
                data = json.loads(message)

                if data.get("event") == "media":
                    payload = data["media"]["payload"]
                    audio_bytes = base64.b64decode(payload)
                    if self._connection:
                        await self._connection.send_media(audio_bytes)

                elif data.get("event") == "stop":
                    logger.info("[SESSION:%s] Twilio stream stopped", self.call_sid)
                    break

        except Exception as exc:
            logger.info("[SESSION:%s] Twilio WebSocket closed: %s", self.call_sid, exc)

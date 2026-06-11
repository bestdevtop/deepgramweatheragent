from deepgram.agent.v1 import (
    AgentV1Settings,
    AgentV1SettingsAgent,
    AgentV1SettingsAgentListen,
    AgentV1SettingsAgentListenProvider_V2,
    AgentV1SettingsAudio,
    AgentV1SettingsAudioInput,
    AgentV1SettingsAudioOutput,
)
from deepgram.types.speak_settings_v1 import SpeakSettingsV1
from deepgram.types.speak_settings_v1provider import SpeakSettingsV1Provider_Deepgram
from deepgram.types.think_settings_v1 import ThinkSettingsV1
from deepgram.types.think_settings_v1functions_item import ThinkSettingsV1FunctionsItem
from deepgram.types.think_settings_v1provider import ThinkSettingsV1Provider_OpenAi

from app.config import settings

SYSTEM_PROMPT = """You are a friendly weather assistant on a phone call.

When the caller asks about weather:
1. If they haven't said a city, ask which city they want to check.
2. You MUST call the check_weather function with the city name before answering.
3. Read the "message" field from the function result naturally to the caller.
4. If is_cold is true, the message field already says whether a text or email reminder was sent — read it naturally.

VOICE FORMATTING RULES:
You are a VOICE agent. Your responses are spoken aloud via text-to-speech.
- Use only plain conversational language
- NO markdown, emojis, brackets, or special formatting
- Keep responses brief: 1-2 sentences per turn
- Spell out numbers naturally when helpful

FUNCTION CALL RULES:
- You MUST call check_weather before giving any weather answer.
- Say something like "Let me check the weather for you" while the function runs.
- After check_weather returns, speak the message field from the result.

When the conversation is naturally over, say goodbye and call end_call.
"""

GREETING = "Hello! I can check today's weather for you. Which city would you like me to check?"

FUNCTIONS = [
    ThinkSettingsV1FunctionsItem(
        name="check_weather",
        description=(
            "Get current weather for a city. You MUST call this before answering "
            "any weather question. Returns temperature, conditions, and a spoken message."
        ),
        parameters={
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City or town name to check",
                },
            },
            "required": ["city"],
        },
    ),
    ThinkSettingsV1FunctionsItem(
        name="end_call",
        description=(
            "End the phone call gracefully after the caller says goodbye "
            "or the conversation has concluded. Say goodbye first, then call this."
        ),
        parameters={
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why the call is ending",
                    "enum": ["weather_provided", "customer_goodbye", "no_action_needed"],
                },
            },
            "required": ["reason"],
        },
    ),
]


def get_agent_config() -> AgentV1Settings:
    return AgentV1Settings(
        type="Settings",
        audio=AgentV1SettingsAudio(
            input=AgentV1SettingsAudioInput(
                encoding="mulaw",
                sample_rate=8000,
            ),
            output=AgentV1SettingsAudioOutput(
                encoding="mulaw",
                sample_rate=8000,
                container="none",
            ),
        ),
        agent=AgentV1SettingsAgent(
            listen=AgentV1SettingsAgentListen(
                provider=AgentV1SettingsAgentListenProvider_V2(
                    version="v2",
                    type="deepgram",
                    model="flux-general-en",
                ),
            ),
            think=ThinkSettingsV1(
                provider=ThinkSettingsV1Provider_OpenAi(
                    type="open_ai",
                    model=settings.llm_model,
                ),
                prompt=SYSTEM_PROMPT,
                functions=FUNCTIONS,
            ),
            speak=SpeakSettingsV1(
                provider=SpeakSettingsV1Provider_Deepgram(
                    type="deepgram",
                    model=settings.voice_model,
                ),
            ),
            greeting=GREETING,
        ),
    )

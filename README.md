# Weather Voice Agent — Deepgram Backend

Alternative backend that provides the same weather + coat-reminder SMS behavior as `backend/`, but uses **Deepgram Voice Agent API** (STT + LLM + TTS) instead of Retell.

## Architecture

```
Caller → Twilio → POST /incoming-call (TwiML)
              → WS /twilio (mulaw audio)
                    ↕
              Deepgram Voice Agent API
                    ↕
              check_weather function → OpenWeatherMap + Twilio SMS
```

Deepgram handles speech-to-text (Flux), reasoning (OpenAI via Deepgram), and text-to-speech (Aura). Weather lookups and SMS are executed locally when the agent calls `check_weather`.

## Quick Start

```bash
cd alternative/backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — at minimum set DEEPGRAM_API_KEY and OPENWEATHER_API_KEY
python main.py
```

Server runs on **port 8001** by default (main backend uses 8000).

## Twilio Setup

1. Expose the server publicly (ngrok, Fly.io, etc.) and set `SERVER_EXTERNAL_URL` in `.env`.
2. In Twilio console, set your phone number's voice webhook to:
   - `https://YOUR-URL/incoming-call` (HTTP POST)
3. Call the number and ask for weather in a city.

When temperature is below `COLD_THRESHOLD_F` (default 50°F), the caller receives a coat-reminder SMS via Twilio.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DEEPGRAM_API_KEY` | Yes | Deepgram API key |
| `OPENWEATHER_API_KEY` | Yes | OpenWeatherMap API key |
| `SERVER_EXTERNAL_URL` | For Twilio | Public URL (e.g. `https://xxxx.ngrok.io`) |
| `TWILIO_*` | For SMS + telephony | Account SID, auth token, from number |
| `COLD_THRESHOLD_F` | No | Cold threshold (default 50) |
| `LLM_MODEL` | No | Default `gpt-4o-mini` |
| `VOICE_MODEL` | No | Default `aura-2-thalia-en` |
| `WEBHOOK_SECRET` | No | Optional path token for `/incoming-call` and `/twilio` |

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | API info |
| GET | `/api/health` | Health check |
| POST | `/incoming-call` | Twilio voice webhook (returns TwiML) |
| WS | `/twilio` | Twilio media stream |

## Tests

```bash
pytest
```

## Comparison with `backend/`

| | `backend/` (Retell) | `alternative/backend/` (Deepgram) |
|--|---------------------|-----------------------------------|
| Voice platform | Retell dashboard | Deepgram Voice Agent API |
| Integration | Retell calls webhook | Twilio streams audio to this server |
| Webhook | `POST /webhook/weather-check` | Function call inside voice session |
| SMS on cold | Yes | Yes |
| OpenWeatherMap | Yes | Yes |

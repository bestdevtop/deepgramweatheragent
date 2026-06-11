# Alternative Backend — Deepgram Weather Voice Agent

Self-contained FastAPI server that runs the full voice stack: **Twilio telephony**, **Deepgram Voice Agent API** (STT + LLM + TTS), **OpenWeatherMap**, and **Twilio SMS** (with optional email fallback).

Use this backend when you want to avoid Retell and host the voice agent yourself via Deepgram.

---

## How It Works

### Call flow

```
Caller dials Twilio number
        │
        ▼
POST /incoming-call  (Twilio voice webhook)
        │
        └──► TwiML: <Connect><Stream url="wss://.../twilio"/></Connect>
                    │
                    ▼
             WebSocket /twilio  (Twilio Media Streams, mulaw 8 kHz)
                    │
                    │  bidirectional audio
                    ▼
             Deepgram Voice Agent API
               • Listen: Flux STT
               • Think: OpenAI LLM (via Deepgram) + function tools
               • Speak: Deepgram Aura TTS
                    │
                    │  LLM invokes check_weather(city)
                    ▼
             function_handlers.py  (in-process, no HTTP round-trip)
                    │
                    ├──► OpenWeatherMap API
                    │
                    ├──► IF cold AND caller phone known AND Twilio configured
                    │         └──► Twilio SMS coat reminder
                    │
                    └──► ELSE IF cold AND email configured
                              └──► SMTP email coat reminder (fallback)
                    │
                    └──► Result JSON → Deepgram → spoken to caller
```

Unlike the Retell backend, this server owns the entire call path: it answers Twilio, bridges audio to Deepgram, and executes weather/SMS logic inside the active voice session.

### Session lifecycle

1. **Incoming call** — Twilio hits `/incoming-call`. The handler validates the Twilio signature (when `TWILIO_AUTH_TOKEN` is set), reads `From` as the caller's phone, and returns TwiML that opens a media stream to `/twilio`.
2. **WebSocket connect** — On `start`, the server creates a `VoiceAgentSession` with `callSid`, `streamSid`, and `caller_phone`.
3. **Deepgram connect** — Session opens a Deepgram agent WebSocket, sends agent settings (prompt, voice model, function definitions), and waits for `SettingsApplied`.
4. **Audio bridge** — Caller audio (Twilio → Deepgram) and agent audio (Deepgram → Twilio) stream concurrently. When the user starts speaking, a `clear` event is sent to Twilio to interrupt agent playback (barge-in).
5. **Function calls** — When the LLM calls `check_weather`, `dispatch_function` runs locally. When it calls `end_call`, the agent says goodbye and the server hangs up via the Twilio REST API after a short delay.
6. **Cleanup** — WebSocket and Deepgram connections are closed when the call ends.

### Cold-weather logic

Same threshold-based behavior as the Retell backend:

1. Fetch weather for the requested city.
2. If temperature ≥ `COLD_THRESHOLD_F` → return a "no coat needed" message.
3. If cold → try SMS to the caller's Twilio `From` number.
4. If SMS fails or Twilio is not configured → try email (when SMTP settings are present).
5. Return a `message` string tailored to what was actually sent.

---

## Project Structure

```
alternative/backend/
├── app/
│   ├── main.py                    # FastAPI app entry
│   ├── config.py                  # Settings from .env
│   ├── routers/
│   │   └── health.py              # GET /api/health
│   ├── telephony/
│   │   └── routes.py              # /incoming-call + /twilio WebSocket
│   ├── voice_agent/
│   │   ├── agent_config.py        # Deepgram agent prompt, voice, functions
│   │   ├── session.py             # Twilio ↔ Deepgram audio bridge
│   │   └── function_handlers.py   # check_weather, end_call
│   └── services/
│       ├── weather.py             # OpenWeatherMap + message builder
│       ├── sms.py                 # Twilio SMS
│       └── email.py               # SMTP coat reminder (fallback)
├── tests/
│   ├── test_health.py
│   ├── test_weather.py
│   └── test_email.py
├── main.py                        # uvicorn entry (port 8001)
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## Setup

```bash
cd alternative/backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — at minimum DEEPGRAM_API_KEY and OPENWEATHER_API_KEY
```

### Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DEEPGRAM_API_KEY` | Yes | Deepgram API key for Voice Agent |
| `OPENWEATHER_API_KEY` | Yes | OpenWeatherMap API key |
| `SERVER_EXTERNAL_URL` | For Twilio | Public HTTPS URL (e.g. `https://xxxx.ngrok.io`) — used in TwiML stream URL |
| `TWILIO_ACCOUNT_SID` | For calls + SMS | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | For calls + SMS | Twilio auth token; also validates webhook signatures |
| `TWILIO_FROM_NUMBER` | For SMS | Twilio sender number (E.164) |
| `COLD_THRESHOLD_F` | No | Cold threshold in °F (default `50`) |
| `LLM_MODEL` | No | OpenAI model via Deepgram (default `gpt-4o-mini`) |
| `VOICE_MODEL` | No | Deepgram TTS voice (default `aura-2-thalia-en`) |
| `SERVER_HOST` | No | Bind address (default `0.0.0.0`) |
| `SERVER_PORT` | No | Listen port (default `8001`) |
| `WEBHOOK_SECRET` | No | Optional path token — `/incoming-call/{token}` and `/twilio/{token}` return 404 on mismatch |
| `FROM_EMAIL`, `TO_EMAIL`, `SMTP_*` | No | Email fallback when SMS is unavailable |

---

## Run

### Development

```bash
python main.py
```

Server listens on **port 8001** by default (the Retell backend uses 8000).

### Docker

```bash
docker build -t weather-agent-deepgram .
docker run --env-file .env -p 8001:8001 weather-agent-deepgram
```

### Twilio setup

1. Expose the server publicly (ngrok, Fly.io, etc.) and set `SERVER_EXTERNAL_URL` in `.env`.
2. In the Twilio console, set your phone number's **Voice webhook** (HTTP POST) to:
   - `https://YOUR-URL/incoming-call`
   - Or `https://YOUR-URL/incoming-call/YOUR_WEBHOOK_SECRET` if `WEBHOOK_SECRET` is set
3. Call the number and ask for weather in a city.

Example with ngrok:

```bash
ngrok http 8001
# Set SERVER_EXTERNAL_URL=https://xxxx.ngrok.io in .env, restart server
```

---

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | API info and endpoint list |
| `GET` | `/api/health` | Health check |
| `POST` | `/incoming-call` | Twilio voice webhook — returns TwiML to start media stream |
| `POST` | `/incoming-call/{token}` | Same, with optional `WEBHOOK_SECRET` |
| `WS` | `/twilio` | Twilio Media Streams WebSocket |
| `WS` | `/twilio/{token}` | Same, with optional `WEBHOOK_SECRET` |

There is no public HTTP weather webhook — `check_weather` runs inside the Deepgram session via `function_handlers.py`.

### Agent functions

| Function | Purpose |
|----------|---------|
| `check_weather(city)` | Fetch weather, send SMS/email if cold, return spoken `message` |
| `end_call(reason)` | Gracefully end the call after goodbye |

Agent prompt, greeting, and function schemas live in `app/voice_agent/agent_config.py`.

---

## Tests

```bash
pytest
```

---

## Comparison with `backend/`

| | `backend/` (Retell) | `alternative/backend/` (this) |
|--|---------------------|----------------------------------|
| Voice platform | Retell dashboard | Deepgram Voice Agent API |
| Telephony | Retell phone number | Twilio Media Streams |
| Weather trigger | Retell POSTs to `/webhook/weather-check` | LLM function call in active session |
| STT / LLM / TTS | Retell-managed | Deepgram Flux + OpenAI + Aura |
| SMS on cold | Twilio | Twilio (+ optional email fallback) |
| Default port | 8000 | 8001 |
| n8n workflow | Supported (same contract) | Not used |

See [`../../backend/README.md`](../../backend/README.md) for the Retell + webhook approach.

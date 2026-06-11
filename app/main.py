import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import health
from app.telephony.routes import router as telephony_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(telephony_router)


@app.get("/")
def root():
    return {
        "message": settings.app_name,
        "voice_provider": "deepgram",
        "endpoints": {
            "health": "/api/health",
            "twilio_webhook": "/incoming-call",
            "twilio_stream": "/twilio",
        },
    }

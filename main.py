import logging

import uvicorn

from app.config import settings

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info(
        "Deepgram API key: %s",
        "configured" if settings.deepgram_api_key else "MISSING",
    )
    if settings.server_external_url:
        logger.info("External URL: %s", settings.server_external_url)
        logger.info("Twilio webhook: %s/incoming-call", settings.server_external_url)
    else:
        logger.info("SERVER_EXTERNAL_URL not set — configure Twilio with your public URL")

    uvicorn.run(
        "app.main:app",
        host=settings.server_host,
        port=settings.server_port,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )

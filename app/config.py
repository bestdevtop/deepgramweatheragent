from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Weather Voice Agent API (Deepgram)"
    cors_origins: list[str] = ["http://localhost:3000"]

    deepgram_api_key: str = ""
    voice_model: str = "aura-2-thalia-en"
    llm_model: str = "gpt-4o-mini"

    server_host: str = "0.0.0.0"
    server_port: int = 8001
    server_external_url: str = ""
    webhook_secret: str = ""

    openweather_api_key: str = ""
    cold_threshold_f: float = 50.0

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""

    from_email: str = ""
    to_email: str = ""
    smtp_password: str = ""
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587


settings = Settings()

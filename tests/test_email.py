from unittest.mock import MagicMock, patch

import pytest

from app.services.email import email_configured, send_coat_reminder_email
from app.services.weather import build_weather_response


def test_email_configured_requires_credentials(monkeypatch):
    monkeypatch.setattr("app.services.email.settings.from_email", "hansonhv@outlook.com")
    monkeypatch.setattr("app.services.email.settings.to_email", "hansonhv@outlook.com")
    monkeypatch.setattr("app.services.email.settings.smtp_password", "")

    assert email_configured() is False

    monkeypatch.setattr("app.services.email.settings.smtp_password", "secret")
    assert email_configured() is True


def test_build_weather_response_cold_with_email():
    weather = {
        "name": "Reykjavik",
        "main": {"temp": 39},
        "weather": [{"description": "snow"}],
    }
    result = build_weather_response(weather, threshold_f=50, email_sent=True)
    assert result["is_cold"] is True
    assert "emailed you" in result["message"]


@patch("app.services.email.smtplib.SMTP")
def test_send_coat_reminder_email(mock_smtp, monkeypatch):
    monkeypatch.setattr("app.services.email.settings.from_email", "hansonhv@outlook.com")
    monkeypatch.setattr("app.services.email.settings.to_email", "hansonhv@outlook.com")
    monkeypatch.setattr("app.services.email.settings.smtp_password", "secret")

    weather = {"name": "London", "main": {"temp": 45}}
    mock_server = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_server

    send_coat_reminder_email(weather)

    mock_smtp.assert_called_once()
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once()
    mock_server.sendmail.assert_called_once()


@pytest.mark.asyncio
@patch("app.voice_agent.function_handlers.send_coat_reminder_email")
@patch("app.voice_agent.function_handlers.send_coat_reminder", side_effect=Exception("sms failed"))
@patch("app.voice_agent.function_handlers.twilio_configured", return_value=True)
@patch("app.voice_agent.function_handlers.email_configured", return_value=True)
@patch("app.voice_agent.function_handlers.fetch_weather")
async def test_check_weather_falls_back_to_email_on_sms_failure(
    mock_fetch_weather,
    _mock_email_configured,
    _mock_twilio_configured,
    _mock_send_sms,
    mock_send_email,
):
    from app.voice_agent.function_handlers import dispatch_function

    mock_fetch_weather.return_value = {
        "name": "London",
        "main": {"temp": 39},
        "weather": [{"description": "cloudy"}],
    }

    result = await dispatch_function("check_weather", {"city": "London"}, caller_phone="+15551234567")

    mock_send_email.assert_called_once()
    assert "emailed you" in result["message"]

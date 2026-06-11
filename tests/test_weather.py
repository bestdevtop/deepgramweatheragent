import pytest

from app.services.weather import build_sms_message, build_weather_response
from app.voice_agent.function_handlers import dispatch_function


def test_build_weather_response_cold_with_sms():
    weather = {
        "name": "Reykjavik",
        "main": {"temp": 39},
        "weather": [{"description": "snow"}],
    }
    result = build_weather_response(weather, threshold_f=50, sms_sent=True)
    assert result["is_cold"] is True
    assert "coat reminder" in result["message"]


def test_build_weather_response_cold_with_sms_and_email():
    weather = {
        "name": "Reykjavik",
        "main": {"temp": 39},
        "weather": [{"description": "snow"}],
    }
    result = build_weather_response(weather, threshold_f=50, sms_sent=True, email_sent=True)
    assert result["is_cold"] is True
    assert "texted and emailed you" in result["message"]


def test_build_weather_response_warm():
    weather = {
        "name": "Dubai",
        "main": {"temp": 89},
        "weather": [{"description": "clear sky"}],
    }
    result = build_weather_response(weather, threshold_f=50)
    assert result["is_cold"] is False
    assert "No coat needed" in result["message"]


def test_build_sms_message():
    weather = {"name": "London", "main": {"temp": 45}}
    sms = build_sms_message(weather)
    assert "London" in sms
    assert "45°F" in sms


@pytest.mark.asyncio
async def test_dispatch_check_weather_missing_city():
    result = await dispatch_function("check_weather", {}, caller_phone="+15551234567")
    assert "city" in result["message"].lower()


@pytest.mark.asyncio
async def test_dispatch_end_call():
    result = await dispatch_function("end_call", {"reason": "customer_goodbye"})
    assert result["status"] == "call_ended"

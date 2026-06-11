from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.runtime_config import reset_recipient_email, set_recipient_email


client = TestClient(app)


def setup_function():
    reset_recipient_email()


def test_get_config_returns_env_values(monkeypatch):
    monkeypatch.setattr("app.routers.config.settings.twilio_from_number", "+15551234567")
    monkeypatch.setattr("app.routers.config.settings.from_email", "sender@example.com")
    monkeypatch.setattr("app.routers.config.settings.to_email", "default@example.com")

    response = client.get("/api/config")

    assert response.status_code == 200
    data = response.json()
    assert data["twilio_from_number"] == "+15551234567"
    assert data["from_email"] == "sender@example.com"
    assert data["recipient_email"] == "default@example.com"


def test_update_recipient_email(monkeypatch):
    monkeypatch.setattr("app.routers.config.settings.twilio_from_number", "+15551234567")
    monkeypatch.setattr("app.routers.config.settings.from_email", "sender@example.com")
    monkeypatch.setattr("app.routers.config.settings.to_email", "default@example.com")

    response = client.put(
        "/api/config/recipient-email",
        json={"recipient_email": "custom@example.com"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["recipient_email"] == "custom@example.com"

    from app.services.runtime_config import get_recipient_email

    assert get_recipient_email() == "custom@example.com"


@patch("app.routers.config.send_test_email", return_value="custom@example.com")
def test_send_test_email_endpoint(_mock_send):
    response = client.post(
        "/api/config/send-test-email",
        json={"recipient_email": "custom@example.com"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["recipient_email"] == "custom@example.com"
    assert "sent" in data["message"].lower()


@patch("app.routers.config.send_test_email", side_effect=Exception("smtp failed"))
def test_send_test_email_endpoint_failure(_mock_send):
    response = client.post("/api/config/send-test-email", json={})

    assert response.status_code == 500

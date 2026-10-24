"""Offline smoke tests: exercise real app lifespan and both QR decoding paths."""
from pathlib import Path

import cv2
import pytest
from fastapi.testclient import TestClient

import qr_module


@pytest.fixture
def client(monkeypatch):
    # Set before importing config/server; dotenv does not override these values.
    monkeypatch.setenv("GEMINI_API_KEY", "offline-smoke-test-not-a-real-key")
    monkeypatch.setenv("ROBOT_ENABLED", "false")
    monkeypatch.setenv("OPENCLAW_FILE_BRIDGE_ENABLED", "false")
    monkeypatch.setenv("SERVER_SSL_ENABLED", "false")
    import server

    assert server.config.ROBOT_ENABLED is False
    assert server.config.OPENCLAW_FILE_BRIDGE_ENABLED is False
    with TestClient(server.app) as test_client:
        yield test_client


@pytest.fixture
def qr_png():
    payload = "alpha-mini-offline-smoke"
    matrix = cv2.QRCodeEncoder_create().encode(payload)
    matrix = cv2.copyMakeBorder(matrix, 4, 4, 4, 4, cv2.BORDER_CONSTANT, value=255)
    image = cv2.resize(matrix, None, fx=8, fy=8, interpolation=cv2.INTER_NEAREST)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    return payload, encoded.tobytes()


def test_app_starts_and_serves_openapi(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Alpha Mini Server"


def test_qr_scanner_static_html_is_served(client):
    response = client.get("/static/qr-scan.html")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    expected = Path(qr_module.__file__).parent / "static" / "qr-scan.html"
    assert response.content == expected.read_bytes()


def test_status_confirms_robot_is_disabled(client):
    response = client.get("/status")
    assert response.status_code == 200
    status = response.json()
    assert status["server"] == "running"
    assert status["robot_enabled"] is False
    assert status["robot_online"] is False


def test_generated_qr_is_decoded(qr_png):
    payload, png = qr_png
    assert any(code["text"] == payload for code in qr_module.decode_qr_codes(png))


def test_qr_uses_cv2_when_pyzbar_is_unavailable(monkeypatch, qr_png):
    payload, png = qr_png
    monkeypatch.setattr(qr_module, "_PYZBAR_OK", False)

    def unexpected_pyzbar_call(_image):
        pytest.fail("pyzbar must not be called when unavailable")

    monkeypatch.setattr(qr_module, "_decode_with_pyzbar", unexpected_pyzbar_call)
    assert qr_module._CV2_OK is True
    assert qr_module.decode_qr_codes(png) == [{"text": payload, "format": "QR_CODE"}]


def test_robot_state_contract(client):
    response = client.get("/robot/state")
    assert response.status_code == 200
    body = response.json()
    assert {"registered", "online", "ip", "battery", "mood", "robot_type"} <= body.keys()
    assert body["registered"] is False
    assert body["online"] is False
    assert body["ip"] is None or isinstance(body["ip"], str)
    assert isinstance(body["robot_type"], str)
    assert body["battery"] is None or isinstance(body["battery"], (int, float))
    assert body["mood"] is None or isinstance(body["mood"], str)


def test_connect_diagnose_contract(client):
    response = client.get("/connect/diagnose")
    assert response.status_code == 200
    body = response.json()
    assert {"server", "robot"} <= body.keys()
    assert {"ok", "version", "uptime_s"} <= body["server"].keys()
    assert body["server"]["ok"] is True
    assert isinstance(body["server"]["version"], str)
    assert isinstance(body["server"]["uptime_s"], int)
    assert body["server"]["uptime_s"] >= 0
    robot = body["robot"]
    assert {"registered", "online", "ip", "battery", "mood", "robot_type"} <= robot.keys()
    assert robot["registered"] is False
    assert robot["online"] is False
    assert robot["ip"] is None or isinstance(robot["ip"], str)
    assert isinstance(robot["robot_type"], str)
    assert robot["battery"] is None or isinstance(robot["battery"], (int, float))
    assert robot["mood"] is None or isinstance(robot["mood"], str)


def test_robot_diagnostic_logs_redact_secrets(client, caplog):
    import logging
    import server
    with caplog.at_level(logging.INFO, logger="server"):
        server._robot_diag("redaction-test", payload={"password": "private-wifi", "token": "private-token", "salt": "private-salt", "AES_KEY": "private-aes"}, message='token=private-inline password="private-inline-password"')
    messages = "\n".join(record.getMessage() for record in caplog.records if "[ROBOT-DIAG]" in record.getMessage())
    assert "redaction-test" in messages
    for secret in ["private-wifi", "private-token", "private-salt", "private-aes", "private-inline", "private-inline-password"]:
        assert secret not in messages
    assert "[REDACTED]" in messages

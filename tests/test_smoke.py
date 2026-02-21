import os

from fastapi.testclient import TestClient

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LOG_LEVEL", "INFO")

from personal_ops_agent.main import app


def test_health_and_chat_smoke() -> None:
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    chat = client.post("/chat", json={"message": "hello"})
    assert chat.status_code == 200

    data = chat.json()
    assert "trace_id" in data
    assert data["intent"] == "unknown"
    assert data["output"] == "OK: hello"
    assert data["state"] == {"intent": "unknown", "output": "OK: hello"}

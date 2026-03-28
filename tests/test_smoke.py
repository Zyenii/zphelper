import os

from fastapi.testclient import TestClient

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LOG_LEVEL", "INFO")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("LLM_ROUTER", "0")
os.environ.setdefault("LLM_PLANNER", "0")
os.environ.setdefault("UNKNOWN_LLM_REPLY", "0")

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
    assert data["state"]["intent"] == "unknown"
    assert data["state"]["output"] == "OK: hello"
    assert "eval" in data["state"]
    assert "runtime" in data["state"]["eval"]


def test_root_ui_page_smoke() -> None:
    client = TestClient(app)
    ui = client.get("/")
    assert ui.status_code == 200
    assert "Personal Ops Agent" in ui.text

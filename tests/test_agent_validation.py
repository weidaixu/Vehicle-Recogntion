from fastapi.testclient import TestClient
from backend.main import app


def test_agent_rejects_empty_and_oversized_request_fields():
    client = TestClient(app)
    for payload in ({"session_id": "", "message": "hello"},
                    {"session_id": "s", "message": ""},
                    {"session_id": "x" * 121, "message": "hello"}):
        assert client.post("/api/agent", json=payload).status_code == 422

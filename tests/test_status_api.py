from fastapi.testclient import TestClient
from backend.main import app

def test_status_contract_hides_credentials():
    data=TestClient(app).get("/api/status").json()
    assert data["model_ready"] is True
    assert data["class_count"] == 51
    assert isinstance(data["macro_f1"],float)
    assert isinstance(data["deepseek_configured"],bool)
    assert "key" not in " ".join(data).lower()

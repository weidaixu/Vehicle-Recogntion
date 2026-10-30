from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from backend.main import app
from backend.routes import agent


def test_agent_continuation_returns_real_trace_shape(monkeypatch):
    class FakeRuntime:
        def run(self, **kwargs):
            assert kwargs["session_id"] == "course-demo"
            assert kwargs["user_message"] == "检索我刚才保存的档案"
            return {
                "session_id": "course-demo",
                "answer": "已找到档案。",
                "classification": None,
                "design_language": None,
                "views": [],
                "board_url": None,
                "trace": [{"tool": "search_archive_history", "status": "success", "arguments": {"query": "刚才"}, "result": {"count": 1}, "duration_ms": 2, "call_id": "c1"}],
            }

    monkeypatch.setattr(agent, "runtime", lambda: FakeRuntime())
    response = TestClient(app).post("/api/agent", json={"session_id": "course-demo", "message": "检索我刚才保存的档案"})

    assert response.status_code == 200
    trace = response.json()["trace"][0]
    assert trace["tool"] == "search_archive_history"
    assert trace["duration_ms"] == 2


def test_agent_upload_rejects_invalid_image_before_model(monkeypatch):
    called = False

    def fail_runtime():
        nonlocal called
        called = True
        raise AssertionError("invalid image must not reach the agent loop")

    monkeypatch.setattr(agent, "runtime", fail_runtime)
    response = TestClient(app).post(
        "/api/agent/upload",
        data={"session_id": "upload-demo", "message": "建立档案"},
        files={"image": ("car.jpg", b"not-a-real-image", "image/jpeg")},
    )

    assert response.status_code == 415
    assert called is False


def test_agent_upload_preserves_unknown_stop_response(monkeypatch):
    class FakeRuntime:
        def run(self, **kwargs):
            return {"session_id": kwargs["session_id"], "answer": "未识别为本组支持的车型。", "classification": {"label": "unknown", "rejected": True, "confidence": .12}, "design_language": None, "views": [], "board_url": None, "trace": [{"tool": "classify_car", "status": "success", "arguments": {"image_ref": kwargs["image_ref"]}, "result": {"label": "unknown"}, "duration_ms": 1, "call_id": "c1"}]}

    monkeypatch.setattr(agent, "runtime", lambda: FakeRuntime())

    image = Image.new("RGB", (8, 8), "gray")
    buf = BytesIO()
    image.save(buf, format="JPEG")
    response = TestClient(app).post("/api/agent/upload", data={"session_id": "unknown-demo", "message": "继续分析"}, files={"image": ("unknown.jpg", buf.getvalue(), "image/jpeg")})

    assert response.status_code == 200
    assert response.json()["classification"]["label"] == "unknown"
    assert [item["tool"] for item in response.json()["trace"]] == ["classify_car"]

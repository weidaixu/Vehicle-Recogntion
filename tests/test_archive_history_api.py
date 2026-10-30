from fastapi.testclient import TestClient

from backend.main import app
from backend.services import services
from backend.session_store import SessionStore


def test_archive_history_endpoint_returns_persisted_records(monkeypatch, tmp_path):
    monkeypatch.setattr(services, "store", SessionStore(tmp_path / "history.sqlite"))
    services.store.save_archive(
        session_id="s1",
        class_id="0000",
        title="车展观察",
        image_ref="img-1.jpg",
        design_language={"summary": "低重心"},
        views=[],
        board_url="/api/design-board/board-1.jpg",
    )

    response = TestClient(app).get("/api/archives", params={"q": "车展"})

    assert response.status_code == 200
    assert response.json()["items"][0]["title"] == "车展观察"
    assert response.json()["items"][0]["class_id"] == "0000"

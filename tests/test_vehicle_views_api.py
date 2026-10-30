from fastapi.testclient import TestClient
from backend.main import app
client=TestClient(app)
def test_local_visual_archive_works_offline():
    data=client.get("/api/vehicle-views/0000?network=false&limit=4").json()
    assert len(data["items"])==4
    assert all(x["source_kind"]=="local_dataset" for x in data["items"])
    assert data["trace_id"]
def test_unknown_class_rejected(): assert client.get("/api/vehicle-views/9999").status_code==404

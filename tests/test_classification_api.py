from pathlib import Path
from fastapi.testclient import TestClient
from backend.main import app

client=TestClient(app)
def test_classify_real_image():
    p=next(Path("prepared_final/val").glob("*/*.jpg"))
    with p.open("rb") as f: response=client.post("/api/classify",files={"image":(p.name,f,"image/jpeg")},data={"threshold":"0.18"})
    assert response.status_code==200; data=response.json(); assert len(data["top_k"])==3; assert 0<=data["confidence"]<=1; assert data["trace_id"]
def test_rejects_invalid_image():
    assert client.post("/api/classify",files={"image":("x.jpg",b"not image","image/jpeg")}).status_code==415

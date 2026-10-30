from fastapi.testclient import TestClient
from backend.main import app
client=TestClient(app)
def test_search_and_detail():
    rows=client.get("/api/cars?q=0000").json(); assert rows[0]["name_from_new"]=="江铃_凯运"
    assert client.get("/api/cars/0000").status_code==200
    assert client.get("/api/cars/9999").status_code==404
